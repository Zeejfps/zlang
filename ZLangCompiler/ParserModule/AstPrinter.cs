using System.Text;
using ParserModule.Nodes;

namespace ParserModule;

public sealed class AstPrinter : IAstNodeVisitor
{
    private readonly StringBuilder _sb = new();
    
    public void VisitIntegerNumberExpression(LiteralIntegerExpressionNode integerNumberExpression)
    {
        _sb.Append(integerNumberExpression.Token.Lexeme);
    }

    public void VisitLiteralBoolExpression(LiteralBoolExpressionNode literalBoolExpressionNode)
    {
        _sb.Append(literalBoolExpressionNode.Token.Lexeme);       
    }

    public void VisitBinaryExpression(BinaryExpressionNode binaryExpressionNode)
    {
        _sb.Append('(');
        binaryExpressionNode.Left.Accept(this);
        _sb.Append(binaryExpressionNode.Op.Lexeme);
        binaryExpressionNode.Right.Accept(this);       
        _sb.Append(')');       
    }

    public void VisitUnaryExpression(UnaryExpressionNode unaryExpressionNode)
    {
        _sb.Append(unaryExpressionNode.Operator.Lexeme);
        unaryExpressionNode.Right.Accept(this);       
    }

    public void VisitIdentifierExpression(IdentifierExpressionNode node)
    {
        _sb.Append(node.Token.Lexeme);
    }

    public void VisitVarAssignmentStatement(VarAssignmentStatementNode node)
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

    public void VisitFunctionDeclarationNode(FunctionDeclarationNode node)
    {
        _sb.Append("func ");
        _sb.Append(node.Name);
        _sb.Append('(');
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
        if (node.Value != null)
        {
            _sb.Append(' ');
            node.Value.Accept(this);
        }
        _sb.Append(';');       
    }

    public override string ToString()
    {
        return _sb.ToString();       
    }
}