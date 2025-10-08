using ParserModule;
using ParserModule.Nodes;

namespace CodeGenModule;

public sealed class CodeGenerator : IAstNodeVisitor
{
    public void VisitLiteralIntegerNode(LiteralIntegerNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitLiteralBoolNode(LiteralBoolNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitBinaryExpression(BinaryExpressionNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitUnaryExpression(UnaryExpressionNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitIdentifierNode(IdentifierNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitVarAssignmentStatement(VarAssignmentStatementNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitNamedTypeNode(NamedTypeNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitBlockStatement(BlockStatementNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitFunctionDeclarationNode(FunctionDeclarationNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitReturnStatementNode(ReturnStatementNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitParameterNode(ParameterNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitStructImportNode(StructImportNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitStructDefinitionNode(StructDefinitionNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitQualifiedIdentifierNode(QualifiedIdentifierNode node)
    {
        throw new NotImplementedException();
    }
}