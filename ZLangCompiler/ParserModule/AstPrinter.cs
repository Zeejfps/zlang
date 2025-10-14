using System.Text;
using ParserModule.Nodes;

namespace ParserModule;

public sealed class AstPrinter : IAstNodeVisitor
{
    private readonly StringBuilder _sb = new();
    
    public void VisitLiteralInteger(LiteralIntegerExpressionNode integerNumberExpression)
    {
        _sb.Append(integerNumberExpression.Token.Lexeme);
    }

    public void VisitLiteralBool(LiteralBoolExpressionNode literalBoolExpressionNode)
    {
        _sb.Append(literalBoolExpressionNode.Token.Lexeme);       
    }

    public void VisitBinary(BinaryExpressionNode binaryExpressionNode)
    {
        _sb.Append('(');
        binaryExpressionNode.Left.Accept(this);
        _sb.Append(binaryExpressionNode.Op.Lexeme);
        binaryExpressionNode.Right.Accept(this);       
        _sb.Append(')');       
    }

    public void VisitUnary(UnaryExpressionNode unaryExpressionNode)
    {
        _sb.Append(unaryExpressionNode.Operator.Lexeme);
        unaryExpressionNode.Right.Accept(this);       
    }

    public void VisitIdentifier(IdentifierExpressionNode node)
    {
        _sb.Append(node.Token.Lexeme);
    }

    public void VisitVarDefinition(VarDefinitionStatementNode node)
    {
        _sb.Append("var ");       
        _sb.Append(node.Name);
        if (node.Type != null)
        {
            _sb.Append(':');
            _sb.Append(' ');
            node.Type.Accept(this);
        }
        _sb.Append(' ');
        _sb.Append('=');
        _sb.Append(' ');
        node.Value.Accept(this);
        _sb.Append(';');       
    }

    public void VisitForStatement(ForStatemetNode node)
    {
        _sb.Append("for (");
        node.Initializer.Accept(this);
        _sb.Append(';');
        node.Condition.Accept(this);
        _sb.Append(';');
        node.Incrementor.Accept(this);
        _sb.Append(')');
        node.Body.Accept(this);       
    }

    public void VisitVarDeclaration(VarDeclarationStatementNode node)
    {
        _sb.Append("var ");
        _sb.Append(node.Name);
        if (node.Type != null)
        {
            _sb.Append(':');
            _sb.Append(' ');
            node.Type.Accept(this);
        }
        _sb.Append(';');       
    }

    public void VisitVarAssignment(VarAssignmentStatementNode node)
    {
        _sb.Append(node.Name);
        _sb.Append(' ');
        _sb.Append('=');
        _sb.Append(' ');
        node.Value.Accept(this);
        _sb.Append(';');       
    }

    public void VisitNamedTypeNode(NamedTypeNode node)
    {
        _sb.Append(node.Name);
    }

    public void VisitBlockStatement(BlockStatementNode node)
    {
        _sb.Append('{');
        _sb.Append('\n');
        foreach (var statement in node.Statements)
        {
            _sb.Append('\t');
            statement.Accept(this);
            _sb.Append('\n');
        }
        _sb.Append('}');
    }

    public void VisitFunctionDeclarationNode(FunctionDefinitionNode node)
    {
        _sb.Append("func ");
        _sb.Append(node.Name);
        _sb.Append('(');
        if (node.Parameters.Count > 0)
        {
            for (var i = 0; i < node.Parameters.Count - 1; i++)
            {
                node.Parameters[i].Accept(this);
                _sb.Append(',');
                _sb.Append(' ');
            }
            node.Parameters[^1].Accept(this);
        }
        _sb.Append(')');
        if (node.ReturnType != null)
        {
            _sb.Append(" -> ");
            node.ReturnType.Accept(this);       
        }
        _sb.Append(' ');
        node.Body.Accept(this);
    }

    public void VisitReturnStatementNode(ReturnStatementNode node)
    {
        _sb.Append("return");
        if (node.Result != null)
        {
            _sb.Append(' ');
            node.Result.Accept(this);
        }
        _sb.Append(';');       
    }

    public void VisitParameterNode(ParameterNode parameterNode)
    {
        _sb.Append(parameterNode.Name);
        _sb.Append(':');
        parameterNode.Type.Accept(this);
    }

    public void VisitStructImportStatementNode(StructImportStatementNode node)
    {
        _sb.Append("struct ");
        _sb.Append(node.AliasName);
        _sb.Append(' ');
        _sb.Append('=');
        _sb.Append(' ');
        var parts = node.QualifiedIdentifier.Parts;
        for (var i = 0; i < parts.Count - 1; i++)
        {
            _sb.Append(parts[i]);
            _sb.Append('.');
        }
        _sb.Append(parts[^1]);
    }

    public void VisitQualifiedIdentifierNode(QualifiedIdentifierNode node)
    {
        for (var i = 0; i < node.Parts.Count - 1; i++)
        {
            _sb.Append(node.Parts[i]);
            _sb.Append('.');
        }
        _sb.Append(node.Parts[^1]);
    }

    public void VisitStructDefinitionNode(StructDefinitionNode node)
    {
        _sb.Append("struct ");
        _sb.Append(node.Name);
        _sb.Append('{');
        _sb.Append('}');
    }

    public void VisitModuleDefinitionNode(ModuleDefinitionNode node)
    {
        throw new NotImplementedException();
    }

    public override string ToString()
    {
        return _sb.ToString();       
    }

    public void VisitIfStatementNode(IfStatementNode node)
    {
        _sb.Append("if ");
        node.Condition.Accept(this);
        _sb.Append(' ');
        node.ThenBranch.Accept(this);
        if (node.ElseBranch != null)
        {
            _sb.Append(" else ");
            node.ElseBranch.Accept(this);
        }
    }
}